from celery import shared_task
import logging
logger = logging.getLogger(__name__)

@shared_task
def aggregate_subid_stats():
    logger.info('SubID stats aggregated')
    return {'aggregated': True}
