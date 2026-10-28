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


# REMOVED: duplicate — canonical in billing_tasks.py


# REMOVED: duplicate — canonical in billing_tasks.py

