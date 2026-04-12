from celery import shared_task
import logging
logger = logging.getLogger(__name__)

@shared_task
def score_all_publishers():
    from django.contrib.auth import get_user_model
    from api.promotions.traffic_quality.quality_scorer import TrafficQualityScorer
    User = get_user_model()
    scorer = TrafficQualityScorer()
    count = 0
    for user in User.objects.filter(is_active=True)[:500]:
        try:
            scorer.calculate_quality_score(user.id)
            count += 1
        except Exception as e:
            logger.error(f'Score failed for user {user.id}: {e}')
    return {'scored': count}
