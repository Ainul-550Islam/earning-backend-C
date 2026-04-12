import logging
import datetime
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('smartlink.tasks.stats')


@shared_task(name='smartlink.hourly_stat_rollup', queue='analytics')
def hourly_stat_rollup():
    """
    Hourly task: Aggregate click data into SmartLinkStat (hourly) and
    SmartLinkDailyStat (daily rollup).
    Runs every 60 minutes via Celery beat.
    """
    from ..models import SmartLink
    from ..services.analytics.SmartLinkAnalyticsService import SmartLinkAnalyticsService

    svc = SmartLinkAnalyticsService()
    now = timezone.now()
    last_hour = now.replace(minute=0, second=0, microsecond=0) - datetime.timedelta(hours=1)

    active_ids = SmartLink.objects.filter(
        is_active=True, is_archived=False
    ).values_list('pk', flat=True)

    count = 0
    for sl_id in active_ids:
        try:
            sl = SmartLink.objects.get(pk=sl_id)
            svc.rollup_hourly_stats(sl, last_hour)
            count += 1
        except Exception as e:
            logger.error(f"Hourly rollup failed for sl#{sl_id}: {e}")

    logger.info(f"Hourly stat rollup complete: {count} smartlinks processed for {last_hour}")
    return {'processed': count, 'hour': str(last_hour)}


@shared_task(name='smartlink.daily_stat_rollup', queue='analytics')
def daily_stat_rollup():
    """
    Daily task: Aggregate hourly stats into SmartLinkDailyStat.
    Runs at 00:05 UTC daily.
    """
    from ..models import SmartLink, SmartLinkStat, SmartLinkDailyStat
    from django.db.models import Sum, Max

    yesterday = timezone.now().date() - datetime.timedelta(days=1)

    active_ids = SmartLink.objects.filter(
        is_active=True
    ).values_list('pk', flat=True)

    updated = 0
    for sl_id in active_ids:
        try:
            hourly = SmartLinkStat.objects.filter(
                smartlink_id=sl_id,
                hour__date=yesterday,
            ).aggregate(
                total_clicks=Sum('clicks'),
                total_unique=Sum('unique_clicks'),
                total_bot=Sum('bot_clicks'),
                total_fraud=Sum('fraud_clicks'),
                total_conversions=Sum('conversions'),
                total_revenue=Sum('revenue'),
            )

            clicks = hourly['total_clicks'] or 0
            revenue = float(hourly['total_revenue'] or 0)
            conversions = hourly['total_conversions'] or 0

            if clicks == 0:
                continue

            # Find top country and device
            top_country_row = SmartLinkStat.objects.filter(
                smartlink_id=sl_id, hour__date=yesterday
            ).values('country').annotate(c=Sum('clicks')).order_by('-c').first()

            top_device_row = SmartLinkStat.objects.filter(
                smartlink_id=sl_id, hour__date=yesterday
            ).values('device_type').annotate(c=Sum('clicks')).order_by('-c').first()

            SmartLinkDailyStat.objects.update_or_create(
                smartlink_id=sl_id,
                date=yesterday,
                defaults={
                    'clicks': clicks,
                    'unique_clicks': hourly['total_unique'] or 0,
                    'bot_clicks': hourly['total_bot'] or 0,
                    'fraud_clicks': hourly['total_fraud'] or 0,
                    'conversions': conversions,
                    'revenue': revenue,
                    'epc': round(revenue / clicks, 4) if clicks else 0,
                    'conversion_rate': round(conversions / clicks, 4) if clicks else 0,
                    'top_country': top_country_row['country'] if top_country_row else '',
                    'top_device': top_device_row['device_type'] if top_device_row else '',
                }
            )
            updated += 1
        except Exception as e:
            logger.error(f"Daily rollup failed for sl#{sl_id}: {e}")

    logger.info(f"Daily stat rollup: {updated} smartlinks for {yesterday}")
    return {'updated': updated, 'date': str(yesterday)}
