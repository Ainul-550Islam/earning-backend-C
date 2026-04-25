# api/notifications/tasks/journey_tasks.py
"""Journey execution Celery tasks."""
import logging
from celery import shared_task
logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2, queue='notifications_campaigns', name='notifications.execute_journey_step')
def execute_journey_step_task(self, user_id: int, journey_id: str, step_id: str, context: dict):
    """Execute one step of a notification journey for a user."""
    try:
        from django.contrib.auth import get_user_model
        from notifications.services.JourneyService import journey_service
        user = get_user_model().objects.get(pk=user_id)
        return journey_service.execute_step(user, journey_id, step_id, context)
    except Exception as exc:
        logger.error(f'execute_journey_step_task {journey_id}/{step_id} user#{user_id}: {exc}')
        try:
            self.retry(exc=exc, countdown=300)
        except Exception:
            return {'success': False, 'error': str(exc)}

@shared_task(queue='notifications_campaigns', name='notifications.enroll_users_in_journey')
def enroll_users_in_journey_task(user_ids: list, journey_id: str, context: dict = None):
    """Enroll multiple users in a journey."""
    from django.contrib.auth import get_user_model
    from notifications.services.JourneyService import journey_service
    User = get_user_model()
    enrolled = 0
    for user in User.objects.filter(pk__in=user_ids, is_active=True):
        result = journey_service.enroll_user(user, journey_id, context or {})
        if result.get('success'):
            enrolled += 1
    return {'enrolled': enrolled, 'total': len(user_ids)}
