import logging
from celery import shared_task

logger = logging.getLogger('smartlink.tasks.epc')


@shared_task(name='smartlink.update_epc_scores', queue='analytics')
def update_epc_scores():
    """
    Every 30 minutes: recalculate EPC scores for all offer/geo/device combos.
    Used by EPC optimizer for traffic routing decisions.
    """
    try:
        from ..services.rotation.EPCOptimizer import EPCOptimizer
        optimizer = EPCOptimizer()
        count = optimizer.recalculate_scores()
        logger.info(f"EPC scores updated: {count} combos recalculated")
        return {'updated': count}
    except Exception as e:
        logger.error(f"update_epc_scores failed: {e}")
        return {'error': str(e)}


@shared_task(name='smartlink.update_epc_for_smartlink', queue='analytics')
def update_epc_for_smartlink(smartlink_id: int):
    """Recalculate EPC for a single SmartLink's offer pool."""
    try:
        from ..services.rotation.EPCOptimizer import EPCOptimizer
        optimizer = EPCOptimizer()
        count = optimizer.recalculate_scores(smartlink_id=smartlink_id)
        logger.info(f"EPC updated for sl#{smartlink_id}: {count} combos")
        return {'smartlink_id': smartlink_id, 'updated': count}
    except Exception as e:
        logger.error(f"update_epc_for_smartlink sl#{smartlink_id} failed: {e}")


@shared_task(name='smartlink.update_offer_performance_stats', queue='analytics')
def update_offer_performance_stats():
    """
    Update OfferPerformanceStat table with latest click+conversion data.
    Runs every 30 minutes alongside EPC update.
    """
    import datetime
    from django.utils import timezone
    from django.db.models import Sum, Count, Q
    from ..models import Click, OfferPerformanceStat

    today = timezone.now().date()
    yesterday = today - datetime.timedelta(days=1)

    for date in [today, yesterday]:
        rows = (
            Click.objects.filter(
                created_at__date=date,
                is_fraud=False,
                is_bot=False,
                offer__isnull=False,
            )
            .values('smartlink_id', 'offer_id', 'country', 'device_type')
            .annotate(
                clicks=Count('id'),
                unique_clicks=Count('id', filter=Q(is_unique=True)),
                conversions=Count('id', filter=Q(is_converted=True)),
                revenue=Sum('payout'),
            )
        )

        for row in rows:
            clicks = row['clicks'] or 0
            revenue = float(row['revenue'] or 0)
            conversions = row['conversions'] or 0

            OfferPerformanceStat.objects.update_or_create(
                smartlink_id=row['smartlink_id'],
                offer_id=row['offer_id'],
                date=date,
                country=row['country'] or '',
                device_type=row['device_type'] or '',
                defaults={
                    'clicks': clicks,
                    'unique_clicks': row['unique_clicks'] or 0,
                    'conversions': conversions,
                    'revenue': revenue,
                    'epc': round(revenue / clicks, 4) if clicks else 0,
                    'conversion_rate': round(conversions / clicks, 4) if clicks else 0,
                }
            )

    logger.info("Offer performance stats updated for today and yesterday")
