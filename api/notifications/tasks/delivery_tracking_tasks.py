# earning_backend/api/notifications/tasks/delivery_tracking_tasks.py
"""
Delivery tracking tasks — poll delivery status, process webhook events,
reconcile undelivered notifications, and update CampaignResult counters.
"""
import logging
from datetime import timedelta

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)


@shared_task(
    queue='notifications_tracking',
    name='notifications.poll_delivery_status',
)
def poll_delivery_status():
    """
    Periodic task: reconcile notifications sent in the last 24 hours
    that are still not marked as delivered.
    Runs every 30 minutes via Celery Beat.
    """
    from notifications.services.DeliveryTracker import delivery_tracker

    result = delivery_tracker.reconcile_undelivered(hours_back=24)
    logger.info(
        f'poll_delivery_status: reconciled={result["reconciled_count"]} '
        f'still_undelivered={result["still_undelivered_count"]} '
        f'errors={result["errors"]}'
    )
    return result


@shared_task(
    queue='notifications_tracking',
    name='notifications.update_campaign_results',
)
def update_campaign_results_task(campaign_id: int):
    """
    Update CampaignResult counters for a specific campaign.
    Called after each batch of campaign sends completes.
    """
    from notifications.services.DeliveryTracker import delivery_tracker

    result = delivery_tracker.update_campaign_results(campaign_id)
    logger.info(
        f'update_campaign_results_task campaign #{campaign_id}: '
        f'delivered={result.get("delivered")} opened={result.get("opened")}'
    )
    return result


@shared_task(
    queue='notifications_tracking',
    name='notifications.update_all_campaign_results',
)
def update_all_active_campaign_results():
    """
    Periodic task: refresh CampaignResult for all campaigns active
    in the last 7 days.
    """
    from notifications.models.campaign import NotificationCampaign
    from notifications.services.DeliveryTracker import delivery_tracker

    cutoff = timezone.now() - timedelta(days=7)
    campaigns = NotificationCampaign.objects.filter(
        status__in=('running', 'completed'),
        updated_at__gte=cutoff,
    ).values_list('pk', flat=True)

    updated = 0
    errors = 0
    for campaign_id in campaigns:
        try:
            delivery_tracker.update_campaign_results(campaign_id)
            updated += 1
        except Exception as exc:
            logger.warning(f'update_all_active_campaign_results #{campaign_id}: {exc}')
            errors += 1

    logger.info(f'update_all_active_campaign_results: updated={updated} errors={errors}')
    return {'updated': updated, 'errors': errors}


@shared_task(
    queue='notifications_tracking',
    name='notifications.process_sendgrid_events',
)
def process_sendgrid_events_task(events: list):
    """
    Process a batch of SendGrid webhook events.
    events: list of SendGrid event dicts from the webhook POST.
    """
    from notifications.services.DeliveryTracker import delivery_tracker

    processed = 0
    errors = 0
    for event in events:
        try:
            result = delivery_tracker.process_sendgrid_event(event)
            if result.get('processed'):
                processed += 1
            else:
                errors += 1
        except Exception as exc:
            logger.warning(f'process_sendgrid_events_task event error: {exc}')
            errors += 1

    return {'processed': processed, 'errors': errors, 'total': len(events)}


@shared_task(
    queue='notifications_tracking',
    name='notifications.process_twilio_webhook',
)
def process_twilio_webhook_task(data: dict):
    """
    Process a Twilio SMS status callback webhook dict.
    """
    from notifications.services.DeliveryTracker import delivery_tracker

    result = delivery_tracker.process_twilio_sms_event(data)
    return result


@shared_task(
    queue='notifications_tracking',
    name='notifications.mark_notification_delivered',
)
def mark_notification_delivered_task(notification_id: int, provider: str = ''):
    """
    Mark a single notification as delivered.
    Called from provider webhook handlers when delivery confirmation arrives.
    """
    from notifications.services.DeliveryTracker import delivery_tracker

    result = delivery_tracker.mark_delivered(notification_id, provider=provider)
    return result


@shared_task(
    queue='notifications_tracking',
    name='notifications.mark_notification_read',
)
def mark_notification_read_task(notification_id: int):
    """Mark a notification as read (called from frontend open events)."""
    from notifications.services.DeliveryTracker import delivery_tracker

    result = delivery_tracker.mark_read(notification_id)
    return result


@shared_task(
    queue='notifications_tracking',
    name='notifications.mark_notification_clicked',
)
def mark_notification_clicked_task(notification_id: int):
    """Record a click event on a notification."""
    from notifications.services.DeliveryTracker import delivery_tracker

    result = delivery_tracker.mark_clicked(notification_id)
    return result


@shared_task(
    queue='notifications_tracking',
    name='notifications.process_push_delivery_receipt',
)
def process_push_delivery_receipt_task(
    notification_id: int,
    device_id: int,
    status: str,
    provider_message_id: str = '',
    error_code: str = '',
    error_message: str = '',
):
    """
    Process a push delivery receipt from FCM / APNs feedback service.

    status: 'delivered' | 'failed' | 'invalid_token'
    """
    from notifications.services.DeliveryTracker import delivery_tracker

    result = delivery_tracker.process_push_delivery_receipt(
        notification_id=notification_id,
        device_id=device_id,
        status=status,
        provider_message_id=provider_message_id,
        error_code=error_code,
        error_message=error_message,
    )
    return result
