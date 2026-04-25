# earning_backend/api/notifications/tasks/send_sms_tasks.py
"""
SMS batch dispatch tasks — routes BD numbers to ShohoSMS, others to Twilio.
"""
import logging
from typing import List

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

BD_PREFIXES = ('01', '+8801', '8801', '0088')


def _is_bd_number(phone: str) -> bool:
    clean = phone.strip().replace(' ', '').replace('-', '').replace('+', '')
    return (
        clean.startswith('01') or
        clean.startswith('8801') or
        clean.startswith('0088')
    )


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue='notifications_sms',
    name='notifications.send_sms_batch',
)
def send_sms_batch_task(self, notification_ids: List[int]):
    """Dispatch SMS for a batch of notification IDs."""
    from api.notifications.models import Notification
    from api.notifications.services.NotificationDispatcher import notification_dispatcher

    success_count = 0
    failure_count = 0

    for nid in notification_ids:
        try:
            notification = Notification.objects.select_related('user').get(
                pk=nid, is_deleted=False
            )
            notification.channel = 'sms'
            result = notification_dispatcher.dispatch(notification)
            if result.get('success'):
                success_count += 1
            else:
                failure_count += 1
        except Notification.DoesNotExist:
            failure_count += 1
        except Exception as exc:
            logger.error(f'send_sms_batch_task #{nid}: {exc}')
            failure_count += 1

    return {'success_count': success_count, 'failure_count': failure_count}


@shared_task(
    bind=True,
    max_retries=2,
    queue='notifications_sms',
    name='notifications.send_bulk_sms',
)
def send_bulk_sms_task(self, recipients: List[dict], body: str):
    """
    Send the same SMS to multiple recipients.
    Recipients: list of {'phone': str, 'notification_id': str}
    Routes BD numbers to ShohoSMS, international to Twilio.
    """
    from api.notifications.services.providers import shoho_sms_provider, twilio_provider

    bd_recipients = [r for r in recipients if _is_bd_number(r.get('phone', ''))]
    intl_recipients = [r for r in recipients if not _is_bd_number(r.get('phone', ''))]

    results = {}

    if bd_recipients and shoho_sms_provider.is_available():
        result = shoho_sms_provider.send_bulk_sms(bd_recipients, body)
        results['bd'] = result

    if intl_recipients and twilio_provider.is_available():
        result = twilio_provider.send_bulk_sms(intl_recipients, body)
        results['international'] = result

    total_success = sum(
        r.get('success_count', 0) for r in results.values()
    )
    total_failure = sum(
        r.get('failure_count', 0) for r in results.values()
    )

    logger.info(f'send_bulk_sms_task: total={len(recipients)} success={total_success} fail={total_failure}')
    return {
        'success': total_success > 0,
        'total': len(recipients),
        'success_count': total_success,
        'failure_count': total_failure,
        'details': results,
    }


@shared_task(
    queue='notifications_sms',
    name='notifications.process_twilio_webhook',
)
def process_twilio_sms_webhook_task(data: dict):
    """Process a Twilio SMS status callback webhook POST data dict."""
    from api.notifications.services.DeliveryTracker import delivery_tracker
    result = delivery_tracker.process_twilio_sms_event(data)
    return result
