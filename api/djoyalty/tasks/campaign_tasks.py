# api/djoyalty/tasks/campaign_tasks.py
"""Campaign automation: start/end campaigns automatically।"""
import logging

try:
    from celery import shared_task
except ImportError:
    def shared_task(func=None, **kwargs):
        if func: return func
        return lambda f: f

logger = logging.getLogger(__name__)


@shared_task(name='djoyalty.activate_due_campaigns', bind=True, max_retries=3, default_retry_delay=60)
def activate_due_campaigns_task(self):
    """Every 15 min: due campaigns activate এবং ended campaigns close করো।"""
    try:
        from django.utils import timezone
        from ..models.campaigns import LoyaltyCampaign

        now = timezone.now()
        # Activate draft campaigns whose start_date has passed
        activated = LoyaltyCampaign.objects.filter(
            status='draft', start_date__lte=now
        ).update(status='active')

        # End active campaigns whose end_date has passed
        ended = LoyaltyCampaign.objects.filter(
            status='active',
            end_date__isnull=False,
            end_date__lt=now,
        ).update(status='ended')

        if activated or ended:
            # Invalidate campaign cache
            try:
                from ..cache_backends import DjoyaltyCache
                DjoyaltyCache.invalidate_campaigns()
            except Exception:
                pass

        logger.info('[djoyalty] Campaigns activated: %d, ended: %d', activated, ended)
        return {'activated': activated, 'ended': ended}
    except Exception as exc:
        logger.error('[djoyalty] activate_due_campaigns error: %s', exc)
        raise self.retry(exc=exc) if hasattr(self, 'retry') else exc


@shared_task(name='djoyalty.notify_campaign_participants', bind=True, max_retries=3, default_retry_delay=120)
def notify_campaign_participants_task(self, campaign_id: int):
    """Campaign শুরু হলে participants কে notify করো।"""
    try:
        from ..models.campaigns import LoyaltyCampaign, CampaignParticipant
        campaign = LoyaltyCampaign.objects.get(id=campaign_id)
        count = CampaignParticipant.objects.filter(campaign=campaign, is_active=True).count()
        logger.info('[djoyalty] Campaign %d started — %d participants to notify', campaign_id, count)
        return count
    except Exception as exc:
        logger.error('[djoyalty] notify_campaign_participants error: %s', exc)
        raise self.retry(exc=exc) if hasattr(self, 'retry') else exc
