from celery import shared_task
import logging
logger = logging.getLogger(__name__)

@shared_task
def sync_vc_rates():
    """Sync virtual currency rates — placeholder."""
    logger.info('VC rates synced')
    return {'synced': True}
