# earning_backend/api/notifications/tasks/campaign_tasks.py
"""
Campaign lifecycle tasks — start/end campaigns, track results.
"""
import logging
from datetime import timedelta

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    queue='notifications_campaigns',
    name='notifications.process_campaign',
)
def process_campaign_task(self, campaign_id: int, batch_size: int = 100):
    """
    Process a running campaign — sends notifications in batches.
    Called after a campaign is started (either immediately or by the
    schedule_tasks.py when send_at is reached).
    """
    from notifications.services.CampaignService import campaign_service

    try:
        result = campaign_service.process_campaign(campaign_id, batch_size=batch_size)
        logger.info(
            f'process_campaign_task #{campaign_id}: '
            f'sent={result.get("total_sent")} failed={result.get("total_failed")} '
            f'status={result.get("campaign_status")}'
        )
        return result
    except Exception as exc:
        logger.error(f'process_campaign_task #{campaign_id} failed: {exc}')
        try:
            self.retry(exc=exc)
        except Exception:
            return {'success': False, 'campaign_id': campaign_id, 'error': str(exc)}


@shared_task(
    queue='notifications_campaigns',
    name='notifications.start_scheduled_campaigns',
)
def start_scheduled_campaigns():
    """
    Periodic task: find campaigns whose send_at has passed and start them.
    Should be scheduled every minute via Celery Beat.
    """
    from notifications.models.campaign import NotificationCampaign

    now = timezone.now()
    due_campaigns = NotificationCampaign.objects.filter(
        status='scheduled',
        send_at__lte=now,
    )

    started = 0
    for campaign in due_campaigns:
        try:
            from notifications.services.CampaignService import campaign_service
            result = campaign_service.start_campaign(campaign.pk)
            if result.get('success'):
                process_campaign_task.delay(campaign.pk)
                started += 1
        except Exception as exc:
            logger.error(f'start_scheduled_campaigns: campaign #{campaign.pk} — {exc}')

    if started:
        logger.info(f'start_scheduled_campaigns: started {started} campaign(s)')
    return {'started': started}


@shared_task(
    queue='notifications_campaigns',
    name='notifications.check_campaign_completion',
)
def check_campaign_completion():
    """
    Periodic task: check for running campaigns that are complete and mark them.
    """
    from notifications.models.campaign import NotificationCampaign

    running = NotificationCampaign.objects.filter(status='running')
    completed = 0

    for campaign in running:
        if campaign.total_users > 0 and (
            campaign.sent_count + campaign.failed_count >= campaign.total_users
        ):
            campaign.complete()
            completed += 1

    return {'completed': completed}


@shared_task(
    queue='notifications_campaigns',
    name='notifications.update_all_campaign_results',
)
def update_all_campaign_results():
    """
    Periodic task: refresh CampaignResult records for all recently active campaigns.
    """
    from notifications.models.campaign import NotificationCampaign
    from notifications.services.DeliveryTracker import delivery_tracker

    cutoff = timezone.now() - timedelta(days=7)
    campaigns = NotificationCampaign.objects.filter(
        status__in=('running', 'completed'),
        updated_at__gte=cutoff,
    )

    updated = 0
    for campaign in campaigns:
        try:
            delivery_tracker.update_campaign_results(campaign.pk)
            updated += 1
        except Exception as exc:
            logger.warning(f'update_all_campaign_results campaign #{campaign.pk}: {exc}')

    return {'updated': updated}
