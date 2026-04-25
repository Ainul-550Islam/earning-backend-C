# tasks/analytics_tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@shared_task
def aggregate_daily_analytics():
    """Daily: aggregate payment analytics."""
    from api.payment_gateways.services.GatewayAnalyticsService import GatewayAnalyticsService
    result = GatewayAnalyticsService().aggregate_daily()
    logger.info(f'Analytics aggregated: {len(result)} combinations')
    return result

@shared_task
def update_success_rates():
    """Hourly: update cached success rates per gateway."""
    from api.payment_gateways.models.reconciliation import PaymentAnalytics
    from django.core.cache import cache
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Avg

    for gw_analytics in PaymentAnalytics.objects.filter(
        date__gte=timezone.now().date() - timedelta(days=7)
    ).values('gateway__name').annotate(avg_rate=Avg('success_rate')):
        gw_name = gw_analytics['gateway__name']
        rate    = float(gw_analytics['avg_rate'] or 0)
        cache.set(f'gw_success_rate:{gw_name}', rate, 7200)
    logger.info('Success rates updated in cache')


@shared_task
def auto_blacklist_low_quality_publishers():
    """Weekly: auto-blacklist publishers with quality score < 20."""
    from api.payment_gateways.blacklist.BlacklistEngine import BlacklistEngine
    count = BlacklistEngine().auto_blacklist_low_quality(threshold=20)
    logger.info(f'Auto-blacklisted {count} low quality publishers')
    return {'blacklisted': count}

@shared_task
def update_offer_quality_scores():
    """Update publisher offer quality scores from conversion data."""
    from api.payment_gateways.blacklist.models import OfferQualityScore
    from api.payment_gateways.tracking.models import Conversion, Click
    from django.db.models import Count, Sum
    from decimal import Decimal

    updated = 0
    for score in OfferQualityScore.objects.filter(total_clicks__gte=50):
        clicks     = score.total_clicks
        conversions= score.total_conversions
        cr         = conversions / max(clicks, 1)
        reversals  = Conversion.objects.filter(
            publisher_id=score.publisher_id, offer_id=score.offer_id,
            status='reversed'
        ).count()
        reversal_rate = reversals / max(conversions, 1)
        quality = int(max(0, min(100,
            cr * 50               # Conversion rate (max 50 pts)
            + (1 - reversal_rate) * 30  # No reversals (max 30 pts)
            + 20                  # Base score
        )))
        score.conversion_rate = Decimal(str(round(cr, 4)))
        score.reversal_rate   = Decimal(str(round(reversal_rate, 4)))
        score.quality_score   = quality
        score.save()
        updated += 1
    return {'updated': updated}
