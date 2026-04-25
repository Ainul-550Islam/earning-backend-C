# earning_backend/api/notifications/tasks/send_email_tasks.py
"""
Email batch dispatch tasks.
"""
import logging
from typing import List

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue='notifications_email',
    name='notifications.send_email_batch',
)
def send_email_batch_task(self, notification_ids: List[int]):
    """Send email for each notification in the batch."""
    from api.notifications.models import Notification
    from api.notifications.services.NotificationDispatcher import notification_dispatcher

    success_count = 0
    failure_count = 0

    for nid in notification_ids:
        try:
            notification = Notification.objects.select_related('user').get(
                pk=nid, is_deleted=False
            )
            notification.channel = 'email'
            result = notification_dispatcher.dispatch(notification)
            if result.get('success'):
                success_count += 1
            else:
                failure_count += 1
        except Notification.DoesNotExist:
            failure_count += 1
        except Exception as exc:
            logger.error(f'send_email_batch_task #{nid}: {exc}')
            failure_count += 1

    return {'success_count': success_count, 'failure_count': failure_count}


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    queue='notifications_email',
    name='notifications.send_bulk_email',
)
def send_bulk_email_task(
    self,
    recipients: List[dict],
    subject: str,
    html_content: str,
    text_content: str = '',
):
    """
    Send a bulk email to multiple recipients via SendGrid personalisations.
    recipients: list of {'email': str, 'name': str, 'substitutions': dict}
    """
    from api.notifications.services.providers import sendgrid_provider

    try:
        result = sendgrid_provider.send_bulk(
            recipients=recipients,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )
        logger.info(
            f'send_bulk_email_task: total={result["total"]} '
            f'success={result["success_count"]} fail={result["failure_count"]}'
        )
        return result
    except Exception as exc:
        logger.error(f'send_bulk_email_task failed: {exc}')
        try:
            self.retry(exc=exc)
        except Exception:
            return {'success': False, 'error': str(exc)}


@shared_task(
    bind=True,
    queue='notifications_email',
    name='notifications.process_sendgrid_webhook',
)
def process_sendgrid_webhook_task(self, events: List[dict]):
    """Process a list of SendGrid webhook events."""
    from api.notifications.services.DeliveryTracker import delivery_tracker

    processed = 0
    for event in events:
        try:
            result = delivery_tracker.process_sendgrid_event(event)
            if result.get('processed'):
                processed += 1
        except Exception as exc:
            logger.warning(f'process_sendgrid_webhook_task event: {exc}')

    return {'processed': processed, 'total': len(events)}
