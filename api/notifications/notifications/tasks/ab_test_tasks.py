# earning_backend/api/notifications/tasks/ab_test_tasks.py
"""
A/B test evaluation tasks.
"""
import logging

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)


@shared_task(
    queue='notifications_campaigns',
    name='notifications.evaluate_ab_test',
)
def evaluate_ab_test_task(ab_test_id: int):
    """
    Evaluate an A/B test and declare a winner.
    Called after a campaign has been running for a sufficient period.
    """
    from api.notifications.services.ABTestService import ab_test_service

    result = ab_test_service.evaluate_winner(ab_test_id)
    logger.info(
        f'evaluate_ab_test_task #{ab_test_id}: '
        f'winner={result.get("winner")} metric={result.get("metric")}'
    )
    return result


@shared_task(
    queue='notifications_campaigns',
    name='notifications.evaluate_all_pending_ab_tests',
)
def evaluate_all_pending_ab_tests():
    """
    Periodic task: evaluate all active A/B tests whose campaigns are completed.
    """
    from api.notifications.models.campaign import CampaignABTest

    pending = CampaignABTest.objects.filter(
        is_active=True,
        campaign__status='completed',
    ).select_related('campaign')

    evaluated = 0
    for ab_test in pending:
        try:
            evaluate_ab_test_task.delay(ab_test.pk)
            evaluated += 1
        except Exception as exc:
            logger.warning(f'evaluate_all_pending_ab_tests #{ab_test.pk}: {exc}')

    return {'queued': evaluated}
