import logging
import datetime
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('smartlink.tasks.heatmap')


@shared_task(name='smartlink.build_heatmaps', queue='analytics')
def build_heatmaps():
    """
    Every 30 minutes: aggregate click data into ClickHeatmap geo records.
    """
    from ..models import SmartLink
    from ..services.analytics.HeatmapService import HeatmapService

    svc = HeatmapService()
    today = timezone.now().date()
    yesterday = today - datetime.timedelta(days=1)

    active = SmartLink.objects.filter(is_active=True, is_archived=False)
    built = 0
    for sl in active:
        for date in [today, yesterday]:
            try:
                svc.build_heatmap_for_date(sl, date)
                built += 1
            except Exception as e:
                logger.error(f"Heatmap build failed sl#{sl.pk} {date}: {e}")

    logger.info(f"Heatmaps built: {built} entries")
    return {'built': built}


@shared_task(name='smartlink.build_heatmap_for_smartlink', queue='analytics')
def build_heatmap_for_smartlink(smartlink_id: int, date_str: str = None):
    """Build heatmap for a single SmartLink on a specific date."""
    from ..models import SmartLink
    from ..services.analytics.HeatmapService import HeatmapService

    svc = HeatmapService()
    date = datetime.date.fromisoformat(date_str) if date_str else timezone.now().date()
    try:
        sl = SmartLink.objects.get(pk=smartlink_id)
        svc.build_heatmap_for_date(sl, date)
        return {'status': 'built', 'smartlink_id': smartlink_id, 'date': str(date)}
    except Exception as e:
        logger.error(f"Heatmap task failed: {e}")
        return {'status': 'error', 'error': str(e)}
