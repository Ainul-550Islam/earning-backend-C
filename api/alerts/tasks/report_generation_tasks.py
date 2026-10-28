"""
report_generation_tasks — Celery tasks for scheduled weekly and monthly
report generation, SLA summary emails, and report distribution.

These tasks complement tasks/reporting.py (which handles on-demand and
daily reports) by owning the weekly/monthly/SLA scheduled pipeline.
"""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta, date

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_range_for_last_week() -> tuple:
    """Return (start_datetime, end_datetime) for the previous calendar week."""
    today = timezone.now().date()
    # Monday of last week
    start_date = today - timedelta(days=today.weekday() + 7)
    end_date = start_date + timedelta(days=6)
    start_dt = timezone.make_aware(
        timezone.datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)
    )
    end_dt = timezone.make_aware(
        timezone.datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)
    )
    return start_dt, end_dt


def _date_range_for_last_month() -> tuple:
    """Return (start_datetime, end_datetime) for the previous calendar month."""
    today = timezone.now().date()
    first_of_this_month = today.replace(day=1)
    last_of_prev_month = first_of_this_month - timedelta(days=1)
    first_of_prev_month = last_of_prev_month.replace(day=1)

    start_dt = timezone.make_aware(
        timezone.datetime(
            first_of_prev_month.year, first_of_prev_month.month, 1, 0, 0, 0
        )
    )
    end_dt = timezone.make_aware(
        timezone.datetime(
            last_of_prev_month.year, last_of_prev_month.month,
            last_of_prev_month.day, 23, 59, 59
        )
    )
    return start_dt, end_dt


def _create_and_generate(title: str, report_type: str,
                          start_dt, end_dt,
                          included_metrics: list,
                          format_type: str = 'json',
                          auto_distribute: bool = False,
                          recipients: list = None):
    """
    Create an AlertReport record, generate its content, and optionally
    distribute it.  Returns the AlertReport instance.
    """
    from ..models.reporting import AlertReport

    report = AlertReport.objects.create(
        title=title,
        report_type=report_type,
        start_date=start_dt,
        end_date=end_dt,
        included_metrics=included_metrics,
        format_type=format_type,
        auto_distribute=auto_distribute,
        recipients=recipients or [],
        status='pending',
    )
    report.generate_report()
    return report


def _distribute_report(report) -> int:
    """
    Send the generated report to its recipients via email notifications.
    Returns the number of notifications created.
    """
    from ..models.core import Notification

    if not report.recipients or report.status != 'completed':
        return 0

    created = 0
    subject = f"Report Ready: {report.title}"
    message = (
        f"Your scheduled report is ready.\n\n"
        f"Title:     {report.title}\n"
        f"Type:      {report.report_type}\n"
        f"Period:    {report.start_date.date()} → {report.end_date.date()}\n"
        f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M UTC') if report.generated_at else 'N/A'}\n\n"
        f"Summary:\n{report.summary}\n"
    )

    for recipient_email in report.recipients:
        if not recipient_email:
            continue
        Notification.objects.create(
            alert_log=None,
            notification_type='email',
            recipient=recipient_email,
            subject=subject,
            message=message,
            status='pending',
        )
        created += 1

    if created:
        try:
            from .notification import send_pending_notifications
            send_pending_notifications.delay()
        except Exception as e:
            logger.error(f"_distribute_report: could not queue send task: {e}")

    return created


# ---------------------------------------------------------------------------
# Weekly report
# ---------------------------------------------------------------------------

@shared_task(
    name='alerts.generate_weekly_report_scheduled',
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=600,
    time_limit=660,
)
def generate_weekly_report_scheduled(self, format_type: str = 'json',
                                     auto_distribute: bool = False,
                                     recipients: list = None):
    """
    Generate the weekly alert report for the previous calendar week.

    Scheduled every Monday at 06:00 via Celery Beat:
        CELERY_BEAT_SCHEDULE = {
            'weekly-report': {
                'task': 'alerts.generate_weekly_report_scheduled',
                'schedule': crontab(hour=6, minute=0, day_of_week='monday'),
            },
        }

    Args:
        format_type:      Output format — 'json', 'csv', 'html', 'pdf'.
        auto_distribute:  If True, email the report to `recipients`.
        recipients:       List of email addresses to receive the report.

    Returns:
        dict with report_id, status, and distribution count.
    """
    try:
        start_dt, end_dt = _date_range_for_last_week()
        title = (
            f"Weekly Alert Report — "
            f"{start_dt.date()} to {end_dt.date()}"
        )

        report = _create_and_generate(
            title=title,
            report_type='weekly',
            start_dt=start_dt,
            end_dt=end_dt,
            included_metrics=[
                'basic_metrics',
                'severity_breakdown',
                'rule_performance',
                'trend_analysis',
                'mttr_summary',
                'sla_compliance',
            ],
            format_type=format_type,
            auto_distribute=auto_distribute,
            recipients=recipients,
        )

        distributed = 0
        if auto_distribute and recipients:
            distributed = _distribute_report(report)

        logger.info(
            f"generate_weekly_report_scheduled: report_id={report.id} "
            f"status={report.status} distributed={distributed}"
        )
        return {
            'report_id': report.id,
            'title': report.title,
            'status': report.status,
            'distributed': distributed,
            'period': f"{start_dt.date()} → {end_dt.date()}",
        }

    except Exception as exc:
        logger.error(f"generate_weekly_report_scheduled error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'error': 'Operation failed'}


# ---------------------------------------------------------------------------
# Monthly report
# ---------------------------------------------------------------------------

@shared_task(
    name='alerts.generate_monthly_report_scheduled',
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=900,
    time_limit=960,
)
def generate_monthly_report_scheduled(self, format_type: str = 'json',
                                      auto_distribute: bool = False,
                                      recipients: list = None):
    """
    Generate the monthly alert report for the previous calendar month.

    Scheduled on the 1st of every month at 07:00 via Celery Beat:
        CELERY_BEAT_SCHEDULE = {
            'monthly-report': {
                'task': 'alerts.generate_monthly_report_scheduled',
                'schedule': crontab(hour=7, minute=0, day_of_month='1'),
            },
        }

    Args:
        format_type:      Output format — 'json', 'csv', 'html', 'pdf'.
        auto_distribute:  If True, email the report to `recipients`.
        recipients:       List of email addresses to receive the report.

    Returns:
        dict with report_id, status, and distribution count.
    """
    try:
        start_dt, end_dt = _date_range_for_last_month()
        month_label = start_dt.strftime('%B %Y')
        title = f"Monthly Alert Report — {month_label}"

        report = _create_and_generate(
            title=title,
            report_type='monthly',
            start_dt=start_dt,
            end_dt=end_dt,
            included_metrics=[
                'basic_metrics',
                'severity_breakdown',
                'rule_performance',
                'trend_analysis',
                'mttr_summary',
                'mttd_summary',
                'sla_compliance',
                'incident_summary',
                'top_rules',
                'channel_performance',
            ],
            format_type=format_type,
            auto_distribute=auto_distribute,
            recipients=recipients,
        )

        distributed = 0
        if auto_distribute and recipients:
            distributed = _distribute_report(report)

        logger.info(
            f"generate_monthly_report_scheduled: report_id={report.id} "
            f"status={report.status} distributed={distributed}"
        )
        return {
            'report_id': report.id,
            'title': report.title,
            'status': report.status,
            'distributed': distributed,
            'period': f"{start_dt.date()} → {end_dt.date()}",
        }

    except Exception as exc:
        logger.error(f"generate_monthly_report_scheduled error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'error': 'Operation failed'}


# ---------------------------------------------------------------------------
# SLA summary report
# ---------------------------------------------------------------------------

@shared_task(
    name='alerts.generate_sla_summary_report',
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    soft_time_limit=600,
    time_limit=660,
)
def generate_sla_summary_report(self, days: int = 30,
                                 format_type: str = 'json',
                                 auto_distribute: bool = False,
                                 recipients: list = None):
    """
    Generate an SLA compliance summary report for the last `days` days.

    Scheduled weekly on Fridays at 17:00 via Celery Beat:
        CELERY_BEAT_SCHEDULE = {
            'sla-summary-report': {
                'task': 'alerts.generate_sla_summary_report',
                'schedule': crontab(hour=17, minute=0, day_of_week='friday'),
                'kwargs': {'days': 7, 'auto_distribute': True},
            },
        }

    Args:
        days:             Number of days to cover (default 30).
        format_type:      Output format.
        auto_distribute:  If True, email the report to `recipients`.
        recipients:       List of email addresses.

    Returns:
        dict with report_id, status, sla_compliance_pct, and distribution count.
    """
    try:
        end_dt = timezone.now()
        start_dt = end_dt - timedelta(days=days)
        title = f"SLA Compliance Report — Last {days} Days ({end_dt.date()})"

        report = _create_and_generate(
            title=title,
            report_type='sla',
            start_dt=start_dt,
            end_dt=end_dt,
            included_metrics=[
                'sla_metrics',
                'resolution_times',
                'compliance_rates',
                'breach_summary',
                'mttr_by_severity',
                'mttd_by_severity',
            ],
            format_type=format_type,
            auto_distribute=auto_distribute,
            recipients=recipients,
        )

        # Extract SLA compliance percentage from generated content
        sla_pct = None
        try:
            sla_pct = (
                report.content
                .get('sla_metrics', {})
                .get('sla_percentage')
            )
        except Exception:
            pass

        distributed = 0
        if auto_distribute and recipients:
            distributed = _distribute_report(report)

        logger.info(
            f"generate_sla_summary_report: report_id={report.id} "
            f"status={report.status} sla_pct={sla_pct} distributed={distributed}"
        )
        return {
            'report_id': report.id,
            'title': report.title,
            'status': report.status,
            'sla_compliance_pct': sla_pct,
            'distributed': distributed,
            'period_days': days,
        }

    except Exception as exc:
        logger.error(f"generate_sla_summary_report error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'error': 'Operation failed'}


# ---------------------------------------------------------------------------
# Recurring report runner
# ---------------------------------------------------------------------------

@shared_task(
    name='alerts.run_due_recurring_reports',
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=580,
    time_limit=600,
)
def run_due_recurring_reports(self):
    """
    Find all AlertReport records with is_recurring=True whose next_run
    timestamp is in the past, generate them, and schedule the next run.

    Scheduled every 15 minutes via Celery Beat:
        CELERY_BEAT_SCHEDULE = {
            'run-due-recurring-reports': {
                'task': 'alerts.run_due_recurring_reports',
                'schedule': crontab(minute='*/15'),
            },
        }

    Returns:
        Number of recurring reports processed.
    """
    try:
        from ..models.reporting import AlertReport

        due_reports = AlertReport.objects.filter(
            is_recurring=True,
            next_run__lte=timezone.now(),
            status__in=['pending', 'completed', 'failed', 'scheduled'],
        )

        processed = 0
        for report in due_reports:
            try:
                # Reset status and regenerate
                report.status = 'pending'
                report.save(update_fields=['status'])
                report.generate_report()

                # Distribute if configured
                if report.auto_distribute and report.recipients:
                    _distribute_report(report)

                # Schedule next run
                report.schedule_next_run()
                processed += 1

                logger.info(
                    f"run_due_recurring_reports: processed report_id={report.id} "
                    f"'{report.title}' next_run={report.next_run}"
                )
            except Exception as e:
                logger.error(
                    f"run_due_recurring_reports: error on report_id={report.id}: {e}",
                    exc_info=True,
                )

        logger.info(f"run_due_recurring_reports: processed {processed} reports")
        return processed

    except Exception as exc:
        logger.error(f"run_due_recurring_reports error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return 0


# ---------------------------------------------------------------------------
# On-demand report generation
# ---------------------------------------------------------------------------

@shared_task(
    name='alerts.generate_report_on_demand',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def generate_report_on_demand(self, report_id: int):
    """
    Generate a specific AlertReport by ID on demand.
    Used by the admin action and API endpoint.

    Args:
        report_id: PK of the AlertReport to generate.

    Returns:
        dict with report_id and status.
    """
    try:
        from ..models.reporting import AlertReport
        report = AlertReport.objects.get(id=report_id)
        report.generate_report()

        if report.auto_distribute and report.recipients:
            _distribute_report(report)

        logger.info(
            f"generate_report_on_demand: report_id={report_id} status={report.status}"
        )
        return {'report_id': report_id, 'status': report.status}

    except Exception as exc:
        logger.error(f"generate_report_on_demand error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'report_id': report_id, 'status': 'failed', 'error': 'Operation failed'}
