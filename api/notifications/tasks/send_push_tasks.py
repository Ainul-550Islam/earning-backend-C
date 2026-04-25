# earning_backend/api/notifications/tasks/send_push_tasks.py
"""
Push notification batch send tasks (FCM / APNs).
"""
import logging
from typing import List

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue='notifications_push',
    name='notifications.send_push_batch',
)
def send_push_batch_task(self, notification_ids: List[int]):
    """
    Send push notifications for a batch of notification IDs.
    Uses FCMProvider multicast for Android/Web and APNsProvider for iOS.
    """
    from notifications.models import Notification, DeviceToken
    from notifications.services.providers import fcm_provider, apns_provider
    from notifications.services import delivery_tracker

    success_count = 0
    failure_count = 0

    for notification_id in notification_ids:
        try:
            notification = Notification.objects.select_related('user').get(
                pk=notification_id, is_deleted=False
            )
            devices = DeviceToken.objects.filter(
                user=notification.user, is_active=True, push_enabled=True
            )

            for device in devices:
                if device.device_type == 'ios' and apns_provider.is_available():
                    token = device.apns_token
                    if token:
                        result = apns_provider.send(token, notification)
                    else:
                        continue
                elif fcm_provider.is_available():
                    token = device.fcm_token or device.get_push_token()
                    if not token or not isinstance(token, str):
                        continue
                    result = fcm_provider.send(token, notification)
                else:
                    continue

                if result.get('success'):
                    success_count += 1
                    device.increment_push_delivered()
                else:
                    failure_count += 1
                    device.increment_push_failed()
                    if result.get('is_invalid_token'):
                        device.deactivate()

        except Notification.DoesNotExist:
            logger.warning(f'send_push_batch_task: notification #{notification_id} not found')
            failure_count += 1
        except Exception as exc:
            logger.error(f'send_push_batch_task: notification #{notification_id} — {exc}')
            failure_count += 1

    logger.info(
        f'send_push_batch_task: processed {len(notification_ids)} — '
        f'success={success_count} failure={failure_count}'
    )
    return {'success_count': success_count, 'failure_count': failure_count}


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue='notifications_push',
    name='notifications.send_push_multicast',
)
def send_push_multicast_task(self, notification_id: int):
    """
    Send a single notification to all user devices using FCM multicast.
    More efficient for users with many devices.
    """
    from notifications.models import Notification, DeviceToken
    from notifications.services.providers import fcm_provider

    try:
        notification = Notification.objects.select_related('user').get(pk=notification_id)
        fcm_tokens = list(
            DeviceToken.objects.filter(
                user=notification.user,
                is_active=True,
                push_enabled=True,
                device_type__in=['android', 'web'],
            ).exclude(fcm_token='').values_list('fcm_token', flat=True)
        )

        if not fcm_tokens:
            return {'success': False, 'error': 'No FCM tokens', 'notification_id': notification_id}

        if not fcm_provider.is_available():
            return {'success': False, 'error': 'FCMProvider not available', 'notification_id': notification_id}

        result = fcm_provider.send_multicast(fcm_tokens, notification)

        # Deactivate invalid tokens
        if result.get('invalid_tokens'):
            DeviceToken.objects.filter(
                fcm_token__in=result['invalid_tokens']
            ).update(is_active=False, updated_at=timezone.now())

        if result.get('success'):
            notification.mark_as_delivered()

        return result

    except Exception as exc:
        logger.error(f'send_push_multicast_task #{notification_id}: {exc}')
        try:
            self.retry(exc=exc)
        except Exception:
            return {'success': False, 'error': str(exc), 'notification_id': notification_id}
