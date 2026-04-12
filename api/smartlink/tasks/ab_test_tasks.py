import logging
from celery import shared_task

logger = logging.getLogger('smartlink.tasks.ab_test')


@shared_task(name='smartlink.evaluate_ab_tests', queue='analytics')
def evaluate_ab_tests():
    """Every hour: evaluate running A/B tests for statistical significance."""
    from ..models import ABTestResult
    from ..choices import ABTestStatus
    from ..services.rotation.ABTestService import ABTestService

    svc = ABTestService()
    running = ABTestResult.objects.filter(status=ABTestStatus.RUNNING)
    winners_found = 0

    for result in running:
        try:
            eval_data = svc.evaluate_significance(result)
            if eval_data.get('significant'):
                winners_found += 1
                logger.info(
                    f"A/B winner found: sl={result.smartlink.slug} "
                    f"variant={eval_data['winner'].name} "
                    f"uplift={eval_data['uplift']:.2f}%"
                )
        except Exception as e:
            logger.error(f"A/B eval failed for result#{result.pk}: {e}")

    logger.info(f"A/B evaluation: {winners_found} winners found from {running.count()} running tests")
    return {'winners_found': winners_found, 'total_evaluated': running.count()}
