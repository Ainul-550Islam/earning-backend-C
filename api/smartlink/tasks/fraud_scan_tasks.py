import logging
import datetime
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('smartlink.tasks.fraud')


@shared_task(name='smartlink.hourly_fraud_scan', queue='fraud')
def hourly_fraud_scan():
    """
    Hourly: Retroactively scan recent clicks for fraud patterns.
    Catches fraud that wasn't caught at redirect time.
    """
    from ..models import Click, ClickFraudFlag
    from ..services.click.ClickFraudService import ClickFraudService

    svc = ClickFraudService()
    cutoff = timezone.now() - datetime.timedelta(hours=1)

    unscanned = Click.objects.filter(
        created_at__gte=cutoff,
        is_fraud=False,
        is_bot=False,
        fraud_score=0,
    ).select_related('smartlink')

    flagged = 0
    for click in unscanned:
        try:
            score, signals = svc.score(click.ip, click.user_agent, {
                'country': click.country,
                'device_type': click.device_type,
            })
            if score >= 60:
                Click.objects.filter(pk=click.pk).update(
                    fraud_score=score,
                    is_fraud=(score >= 85),
                )
                svc.create_fraud_flag(
                    click=click, score=score, signals=signals,
                    action='block' if score >= 85 else 'flag',
                )
                flagged += 1
        except Exception as e:
            logger.warning(f"Fraud scan error for click#{click.pk}: {e}")

    logger.info(f"Fraud scan: {flagged} clicks flagged out of {unscanned.count()} scanned")
    return {'flagged': flagged}


@shared_task(name='smartlink.scan_high_velocity_ips', queue='fraud')
def scan_high_velocity_ips():
    """
    Every 15 minutes: find IPs with abnormally high click volumes and auto-block.
    """
    from django.db.models import Count
    from django.core.cache import cache
    from ..models import Click
    from ..constants import MAX_CLICKS_PER_IP_PER_HOUR

    cutoff = timezone.now() - datetime.timedelta(hours=1)
    high_velocity = (
        Click.objects.filter(created_at__gte=cutoff)
        .values('ip')
        .annotate(cnt=Count('id'))
        .filter(cnt__gt=MAX_CLICKS_PER_IP_PER_HOUR)
    )

    blocked = 0
    for row in high_velocity:
        ip = row['ip']
        cache.set(f"fraud:blocked:{ip}", '1', 3600)
        logger.warning(f"Auto-blocked high-velocity IP: {ip} ({row['cnt']} clicks/hr)")
        blocked += 1

    return {'blocked': blocked}
