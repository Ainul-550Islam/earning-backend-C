"""
api/support/reports/scheduled_reports.py
FILE 54/70 — Auto Email Reports (Scheduled)

Celery beat-এ daily/weekly/monthly reports পাঠাও।
"""
import logging
from django.conf import settings
from django.utils import timezone
logger = logging.getLogger(__name__)

ADMIN_EMAIL = getattr(settings, 'SUPPORT_ADMIN_EMAIL', '')

class ScheduledReports:
    def send_daily_report(self) -> bool:
        from api.support.reports.ticket_report import ticket_report
        from api.support.notifications.email_notifier import email_notifier
        if not ADMIN_EMAIL:
            return False
        data    = ticket_report.generate(days=1)
        summary = data.get('summary', {})
        return email_notifier.daily_digest(ADMIN_EMAIL, {
            'created':  summary.get('total', 0),
            'resolved': summary.get('resolved', 0),
            'open':     summary.get('open', 0),
            'csat':     summary.get('csat_score', 0),
            'sla_rate': 0,
            'date':     timezone.now().strftime('%d %b %Y'),
        })

    def send_weekly_report(self) -> bool:
        from api.support.reports.ticket_report import ticket_report
        from api.support.reports.csat_report import csat_report
        from api.support.notifications.email_notifier import email_notifier
        if not ADMIN_EMAIL:
            return False
        ticket_data = ticket_report.generate(days=7)
        csat_data   = csat_report.generate(days=7)
        summary     = ticket_data.get('summary', {})
        subject = f'📊 Weekly Support Report — {timezone.now().strftime("%d %b %Y")}'
        body    = (
            f'Weekly Support Summary\n\n'
            f'Tickets: {summary.get("total",0)} created, {summary.get("resolved",0)} resolved\n'
            f'Resolution Rate: {summary.get("resolution_rate_pct",0)}%\n'
            f'Avg Response: {summary.get("avg_first_response_min",0)} min\n'
            f'CSAT: {csat_data.get("avg_score",0)}/5.0\n'
            f'NPS: {csat_data.get("nps_score",0)}\n'
        )
        return email_notifier._send(ADMIN_EMAIL, subject, body)

    def send_monthly_report(self) -> bool:
        from api.support.reports.ticket_report import ticket_report
        from api.support.reports.agent_report import agent_report
        if not ADMIN_EMAIL:
            return False
        ticket_data = ticket_report.generate(days=30)
        summary     = ticket_data.get('summary', {})
        subject = f'📈 Monthly Support Report — {timezone.now().strftime("%B %Y")}'
        from api.support.notifications.email_notifier import email_notifier
        body = (
            f'Monthly Support Report — {timezone.now().strftime("%B %Y")}\n\n'
            f'Total Tickets: {summary.get("total",0)}\n'
            f'Resolved: {summary.get("resolved",0)} ({summary.get("resolution_rate_pct",0)}%)\n'
            f'Escalated: {summary.get("escalated",0)}\n'
            f'Avg Response: {summary.get("avg_first_response_min",0)} min\n'
            f'Avg Resolution: {summary.get("avg_resolution_hrs",0)} hrs\n'
            f'CSAT: {summary.get("csat_score",0)}/5.0\n'
        )
        return email_notifier._send(ADMIN_EMAIL, subject, body)

scheduled_reports = ScheduledReports()