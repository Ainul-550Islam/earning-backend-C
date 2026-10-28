# api/admin_panel/services/AdminNotificationService.py
"""Service for sending system notifications to admin users."""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AdminNotificationService:

    @classmethod
    def notify_report_ready(cls, export) -> bool:
        """Send notification when a ReportExport is completed."""
        try:
            if not export.generated_by or not export.generated_by.email:
                return False
            from ..models.config import EmailTemplate
            from ..utils import send_admin_email_notification
            template = EmailTemplate.get_template('report_ready')
            report_name = export.report.name if export.report else 'Report'
            if template:
                rendered = template.render({
                    'user_name': export.generated_by.get_full_name() or export.generated_by.username,
                    'report_name': report_name,
                    'row_count': export.row_count,
                    'format': export.format.upper(),
                    'download_url': export.file_url,
                })
                subject = rendered['subject']
                body = rendered['text'] or rendered['html']
            else:
                subject = f"[Report Ready] {report_name}"
                body = (
                    f"Hello {export.generated_by.username},\n\n"
                    f"Your report '{report_name}' is ready.\n"
                    f"Rows: {export.row_count} | Format: {export.format.upper()}\n"
                    f"Download: {export.file_url}\n\n"
                    f"This link expires in 7 days."
                )
            return send_admin_email_notification(subject, body, [export.generated_by.email])
        except Exception as e:
            logger.error(f"notify_report_ready failed: {e}")
            return False

    @classmethod
    def notify_maintenance_upcoming(cls, window) -> bool:
        """Notify all active users of upcoming maintenance."""
        try:
            from django.contrib.auth import get_user_model
            from ..utils import send_admin_email_notification
            User = get_user_model()
            emails = list(
                User.objects.filter(is_active=True).exclude(email='').values_list('email', flat=True)[:5000]
            )
            if not emails:
                return False
            subject = f"Scheduled Maintenance: {window.title}"
            body = (
                f"We will be performing maintenance:\n"
                f"Start: {window.start_at.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"Duration: {window.duration_minutes} minutes\n\n"
                f"{window.message}"
            )
            for i in range(0, len(emails), 100):
                try:
                    send_admin_email_notification(subject, body, emails[i:i + 100])
                except Exception as e:
                    logger.warning(f"Batch notification failed: {e}")
            return True
        except Exception as e:
            logger.error(f"notify_maintenance_upcoming failed: {e}")
            return False

    @classmethod
    def notify_system_health_alert(cls, health: dict) -> bool:
        """Send system health alert to superadmins."""
        try:
            from django.contrib.auth import get_user_model
            from ..utils import send_admin_email_notification
            User = get_user_model()
            emails = list(
                User.objects.filter(is_superuser=True, is_active=True).exclude(email='').values_list('email', flat=True)
            )
            if not emails:
                return False
            failing = [k for k, v in health.get('checks', {}).items() if v.get('status') != 'healthy']
            subject = f"[ALERT] System Health: {health.get('overall', '?').upper()} — {', '.join(failing)}"
            body = (
                f"System health alert at {health.get('checked_at', '?')}:\n\n"
                + '\n'.join(f"  - {k}: {v.get('status')} {v.get('error', '')}"
                            for k, v in health.get('checks', {}).items())
                + "\n\nPlease investigate immediately."
            )
            return send_admin_email_notification(subject, body, emails)
        except Exception as e:
            logger.error(f"notify_system_health_alert failed: {e}")
            return False

    @classmethod
    def send_admin_digest(cls, stats: dict, recipients: list) -> bool:
        """Send daily admin digest to specified recipients."""
        try:
            from ..utils import send_admin_email_notification
            date = stats.get('date', 'Yesterday')
            subject = f"[Admin Digest] Daily Summary — {date}"
            body = (
                f"Admin Digest — {date}\n"
                f"{'=' * 40}\n"
                f"New Users:          {stats.get('new_users', 'N/A')}\n"
                f"Total Users:        {stats.get('total_users', 'N/A')}\n"
                f"Revenue:            ৳{stats.get('revenue', 0):,}\n"
                f"Withdrawal Requests:{stats.get('withdrawal_requests', 'N/A')}\n"
                f"Pending:            {stats.get('pending_withdrawals', 'N/A')}\n"
                f"Admin Actions:      {stats.get('admin_actions', 'N/A')}\n"
                f"Critical Alerts:    {len(stats.get('critical_insights', []))}\n"
            )
            return send_admin_email_notification(subject, body, recipients)
        except Exception as e:
            logger.error(f"send_admin_digest failed: {e}")
            return False