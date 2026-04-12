import logging
from celery import shared_task

logger = logging.getLogger('smartlink.tasks.offer_score')


@shared_task(name='smartlink.update_offer_scores', queue='analytics')
def update_offer_scores():
    """Every 30 minutes: refresh OfferScoreCache for all active offers."""
    from ..services.rotation.OfferScoreService import OfferScoreService
    from ..models import OfferPoolEntry
    from django.db.models import Sum, Count
    import datetime
    from django.utils import timezone

    svc = OfferScoreService()
    cutoff = timezone.now().date() - datetime.timedelta(days=7)
    from ..models import OfferPerformanceStat

    rows = (
        OfferPerformanceStat.objects.filter(date__gte=cutoff)
        .values('offer_id', 'country', 'device_type')
        .annotate(
            clicks=Sum('clicks'),
            conversions=Sum('conversions'),
            revenue=Sum('revenue'),
        )
    )

    updated = 0
    for row in rows:
        svc.update_score(
            offer_id=row['offer_id'],
            country=row['country'],
            device_type=row['device_type'],
            clicks=row['clicks'] or 0,
            conversions=row['conversions'] or 0,
            revenue=float(row['revenue'] or 0),
        )
        updated += 1

    logger.info(f"Offer scores updated: {updated} combos")
    return {'updated': updated}
