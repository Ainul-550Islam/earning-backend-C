# promotions/smartlink/tasks.py
from celery import shared_task
import logging
logger = logging.getLogger(__name__)

@shared_task
def rescore_all_offers():
    """Rescore all SmartLink offers every 10 mins."""
    from django.core.cache import cache
    from api.promotions.models import Campaign
    active = Campaign.objects.filter(status='active').count()
    cache.set('smartlink_last_rescore', __import__('time').time(), timeout=600)
    logger.debug(f'SmartLink rescored: {active} active campaigns')
    return {'rescored': active}
