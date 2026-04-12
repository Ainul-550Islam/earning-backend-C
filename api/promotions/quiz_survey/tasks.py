from celery import shared_task
import logging
logger = logging.getLogger(__name__)

@shared_task
def refresh_active_quizzes():
    logger.info('Quiz refresh task ran')
    return {'refreshed': True}
