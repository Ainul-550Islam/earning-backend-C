"""
oncall_notify_tasks — Celery tasks that notify the on-call person when a
new incident is created, when an escalation fires, and when the rotation
changes.  All notification delivery goes through the existing Notification
model and NotificationService so channel routing, rate-limiting, and retry
logic are handled in one place.
"""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_current_oncall_users() -> list:
    """
    Return a list of User objects who are currently on-call across all
    active OnCallSchedule instances.
    """
    from ..models.incident import OnCallSchedule
    on_call_users = []
    for schedule in OnCallSchedule.objects.filter(is_active=True):
        user = schedule.get_current_on_call()
        if user and user not in on_call_users:
            on_call_users.append(user)
    return on_call_users


def _create_notification(recipient_email: str, subject: str, message: str,
                         alert_log=None, notification_type: str = 'email'):
    """
    Create a Notification record and queue it for delivery.
    alert_log may be None for schedule-change notifications.
    """
    from ..models.core import Notification
    notification = Notification.objects.create(
        alert_log=alert_log,
        notification_type=notification_type,
        recipient=recipient_email,
        subject=subject,
        message=message,
        status='pending',
    )
    return notification


def _queue_send():
    """Trigger the send_pending_notifications task asynchronously."""
    try:
        from .notification import send_pending_notifications
        send_pending_notifications.delay()
    except Exception as e:
        logger.error(f"_queue_send: could not trigger send_pending_notifications: {e}")


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@shared_task(
    name='alerts.notify_oncall_new_incident',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def notify_oncall_new_incident(self, incident_id: int):
    """
    Notify all currently on-call users that a new incident has been created.

    Called by the incident_post_save signal or IncidentService.create().

    Args:
        incident_id: PK of the newly created Incident.

    Returns:
        Number of notifications created.
    """
    try:
        from ..models.incident import Incident

        incident = Incident.objects.select_related('assigned_to').get(id=incident_id)
        on_call_users = _get_current_oncall_users()

        if not on_call_users:
            logger.warning(
                f"notify_oncall_new_incident: no on-call users found for incident {incident_id}"
            )
            return 0

        subject = f"[{incident.severity.upper()}] New Incident: {incident.title}"
        message = (
            f"A new incident has been created and requires your attention.\n\n"
            f"Title:    {incident.title}\n"
            f"Severity: {incident.severity.upper()}\n"
            f"Impact:   {incident.impact}\n"
            f"Status:   {incident.status}\n"
            f"Detected: {incident.detected_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"{incident.description}\n\n"
            f"Please acknowledge and begin investigation immediately."
        )

        created = 0
        for user in on_call_users:
            if not user.email:
                continue
            _create_notification(
                recipient_email=user.email,
                subject=subject,
                message=message,
                notification_type='email',
            )
            created += 1

        _queue_send()
        logger.info(
            f"notify_oncall_new_incident: incident={incident_id} "
            f"notified {created} on-call user(s)"
        )
        return created

    except Exception as exc:
        logger.error(f"notify_oncall_new_incident error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return 0


@shared_task(
    name='alerts.notify_oncall_escalation',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def notify_oncall_escalation(self, incident_id: int, escalation_level: int):
    """
    Notify the escalation chain when an incident is escalated to a new level.

    Args:
        incident_id:       PK of the Incident being escalated.
        escalation_level:  The new escalation level (1-based).

    Returns:
        Number of notifications created.
    """
    try:
        from ..models.incident import Incident, OnCallSchedule

        incident = Incident.objects.get(id=incident_id)

        # Collect escalation targets from all active schedules
        escalation_users = []
        for schedule in OnCallSchedule.objects.filter(is_active=True):
            chain = schedule.get_escalation_chain()
            for entry in chain:
                if entry.get('level', 0) >= escalation_level:
                    user = entry.get('user')
                    if user and user not in escalation_users:
                        escalation_users.append(user)

        if not escalation_users:
            # Fall back to current on-call
            escalation_users = _get_current_oncall_users()

        if not escalation_users:
            logger.warning(
                f"notify_oncall_escalation: no escalation targets for "
                f"incident {incident_id} level {escalation_level}"
            )
            return 0

        subject = (
            f"[ESCALATED L{escalation_level}] [{incident.severity.upper()}] "
            f"{incident.title}"
        )
        message = (
            f"Incident has been escalated to level {escalation_level}.\n\n"
            f"Title:       {incident.title}\n"
            f"Severity:    {incident.severity.upper()}\n"
            f"Status:      {incident.status}\n"
            f"Detected:    {incident.detected_at.strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Escalated:   {timezone.now().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"Description: {incident.description}\n\n"
            f"Immediate action is required. Please acknowledge this incident."
        )

        created = 0
        for user in escalation_users:
            if not user.email:
                continue
            _create_notification(
                recipient_email=user.email,
                subject=subject,
                message=message,
                notification_type='email',
            )
            created += 1

        _queue_send()
        logger.info(
            f"notify_oncall_escalation: incident={incident_id} "
            f"level={escalation_level} notified {created} user(s)"
        )
        return created

    except Exception as exc:
        logger.error(f"notify_oncall_escalation error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return 0


@shared_task(
    name='alerts.notify_oncall_rotation_change',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def notify_oncall_rotation_change(self, schedule_id: int):
    """
    Notify the outgoing and incoming on-call users when a rotation changes.

    Args:
        schedule_id: PK of the OnCallSchedule that rotated.

    Returns:
        Number of notifications created.
    """
    try:
        from ..models.incident import OnCallSchedule

        schedule = OnCallSchedule.objects.prefetch_related(
            'primary_users', 'backup_users', 'escalation_users'
        ).get(id=schedule_id)

        current_user = schedule.get_current_on_call()
        upcoming = schedule.get_upcoming_schedule(days=1)

        created = 0

        # Notify the new on-call person
        if current_user and current_user.email:
            subject = f"You are now on-call: {schedule.name}"
            message = (
                f"You have started your on-call shift for schedule '{schedule.name}'.\n\n"
                f"Schedule type: {schedule.schedule_type}\n"
                f"Timezone:      {schedule.timezone}\n"
                f"Hours:         {schedule.start_time} – {schedule.end_time}\n\n"
                f"Please ensure you are reachable and have the alert app open.\n"
                f"Escalation delay: {schedule.escalation_minutes} minutes."
            )
            _create_notification(
                recipient_email=current_user.email,
                subject=subject,
                message=message,
                notification_type='email',
            )
            created += 1

        # Notify the next person in the upcoming schedule (handoff notice)
        if upcoming:
            next_entry = upcoming[0]
            next_user = next_entry.get('user')
            next_date = next_entry.get('date')
            if next_user and next_user != current_user and next_user.email:
                subject = f"Upcoming on-call shift: {schedule.name} on {next_date}"
                message = (
                    f"This is a reminder that you are scheduled to be on-call.\n\n"
                    f"Schedule: {schedule.name}\n"
                    f"Date:     {next_date}\n"
                    f"Hours:    {schedule.start_time} – {schedule.end_time} ({schedule.timezone})\n\n"
                    f"Please ensure your contact details are up to date."
                )
                _create_notification(
                    recipient_email=next_user.email,
                    subject=subject,
                    message=message,
                    notification_type='email',
                )
                created += 1

        _queue_send()
        logger.info(
            f"notify_oncall_rotation_change: schedule={schedule_id} "
            f"created {created} notification(s)"
        )
        return created

    except Exception as exc:
        logger.error(f"notify_oncall_rotation_change error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return 0


@shared_task(
    name='alerts.notify_oncall_unacknowledged_alert',
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def notify_oncall_unacknowledged_alert(self, alert_log_id: int):
    """
    Notify on-call users about a high/critical alert that has not been
    acknowledged within the rule's cooldown window.

    Args:
        alert_log_id: PK of the AlertLog that is unacknowledged.

    Returns:
        Number of notifications created.
    """
    try:
        from ..models.core import AlertLog

        alert_log = AlertLog.objects.select_related('rule').get(id=alert_log_id)

        # Only proceed if still unresolved
        if alert_log.is_resolved:
            logger.info(
                f"notify_oncall_unacknowledged_alert: alert {alert_log_id} "
                f"already resolved — skipping"
            )
            return 0

        on_call_users = _get_current_oncall_users()
        if not on_call_users:
            logger.warning(
                f"notify_oncall_unacknowledged_alert: no on-call users for alert {alert_log_id}"
            )
            return 0

        age_minutes = alert_log.age_in_minutes
        subject = (
            f"[UNACKNOWLEDGED] [{alert_log.rule.severity.upper()}] "
            f"{alert_log.rule.name}"
        )
        message = (
            f"The following alert has NOT been acknowledged and requires immediate attention.\n\n"
            f"Rule:      {alert_log.rule.name}\n"
            f"Severity:  {alert_log.rule.severity.upper()}\n"
            f"Type:      {alert_log.rule.alert_type}\n"
            f"Value:     {alert_log.trigger_value} (threshold: {alert_log.threshold_value})\n"
            f"Triggered: {alert_log.triggered_at.strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Age:       {age_minutes:.0f} minutes\n\n"
            f"Message: {alert_log.message}\n\n"
            f"Please investigate and resolve this alert immediately."
        )

        created = 0
        for user in on_call_users:
            if not user.email:
                continue
            _create_notification(
                recipient_email=user.email,
                subject=subject,
                message=message,
                notification_type='email',
            )
            created += 1

        _queue_send()
        logger.info(
            f"notify_oncall_unacknowledged_alert: alert={alert_log_id} "
            f"age={age_minutes:.0f}min notified {created} user(s)"
        )
        return created

    except Exception as exc:
        logger.error(f"notify_oncall_unacknowledged_alert error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return 0


@shared_task(
    name='alerts.check_and_notify_unacknowledged_alerts',
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=280,
    time_limit=300,
)
def check_and_notify_unacknowledged_alerts(self, threshold_minutes: int = 15):
    """
    Periodic task: find all high/critical unresolved alerts older than
    `threshold_minutes` and dispatch notify_oncall_unacknowledged_alert
    for each one.

    Scheduled every 5 minutes via Celery Beat:
        CELERY_BEAT_SCHEDULE = {
            'check-unacknowledged-alerts': {
                'task': 'alerts.check_and_notify_unacknowledged_alerts',
                'schedule': crontab(minute='*/5'),
            },
        }

    Args:
        threshold_minutes: alerts older than this are considered unacknowledged.

    Returns:
        Number of alerts dispatched for notification.
    """
    try:
        from ..models.core import AlertLog
        cutoff = timezone.now() - timedelta(minutes=threshold_minutes)

        unacknowledged = AlertLog.objects.filter(
            is_resolved=False,
            triggered_at__lte=cutoff,
            rule__severity__in=['high', 'critical'],
        ).select_related('rule')

        dispatched = 0
        for alert_log in unacknowledged:
            # Avoid re-notifying if we already sent a notification recently
            already_notified = alert_log.details.get('oncall_notified_at')
            if already_notified:
                from django.utils.dateparse import parse_datetime
                notified_at = parse_datetime(already_notified)
                if notified_at and (timezone.now() - notified_at).total_seconds() < 900:
                    # Notified within last 15 minutes — skip
                    continue

            notify_oncall_unacknowledged_alert.delay(alert_log.id)

            # Record that we dispatched a notification
            alert_log.details['oncall_notified_at'] = timezone.now().isoformat()
            alert_log.save(update_fields=['details'])
            dispatched += 1

        logger.info(
            f"check_and_notify_unacknowledged_alerts: "
            f"dispatched {dispatched} notification tasks"
        )
        return dispatched

    except Exception as exc:
        logger.error(f"check_and_notify_unacknowledged_alerts error: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return 0
