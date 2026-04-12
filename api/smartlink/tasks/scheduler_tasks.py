import logging
from celery import shared_task

logger = logging.getLogger('smartlink.tasks.scheduler')


@shared_task(name='smartlink.process_schedules', queue='default')
def process_schedules():
    """Every minute: evaluate SmartLink schedules and auto-activate/deactivate."""
    from ..services.scheduler.SmartLinkSchedulerService import SmartLinkSchedulerService
    svc    = SmartLinkSchedulerService()
    result = svc.process_all_schedules()
    if result['activated'] or result['deactivated']:
        logger.info(
            f"Schedules: activated={result['activated']} "
            f"deactivated={result['deactivated']}"
        )
    return result


@shared_task(name='smartlink.evaluate_publisher_tiers', queue='analytics')
def evaluate_publisher_tiers():
    """Weekly: re-evaluate all publisher quality tiers."""
    from django.contrib.auth import get_user_model
    from ..services.publisher.PublisherTierService import PublisherTierService

    User = get_user_model()
    svc  = PublisherTierService()

    publishers = User.objects.filter(
        is_active=True, smartlinks__isnull=False
    ).distinct()

    evaluated = 0
    for pub in publishers:
        try:
            svc.evaluate_publisher(pub)
            evaluated += 1
        except Exception as e:
            logger.error(f"Tier eval failed for publisher#{pub.pk}: {e}")

    logger.info(f"Publisher tiers evaluated: {evaluated}")
    return {'evaluated': evaluated}


@shared_task(name='smartlink.update_currency_rates', queue='default')
def update_currency_rates():
    """Every hour: fetch live exchange rates."""
    from ..services.currency.MultiCurrencyService import MultiCurrencyService
    svc     = MultiCurrencyService()
    success = svc.update_rates_from_api()
    return {'updated': success}
